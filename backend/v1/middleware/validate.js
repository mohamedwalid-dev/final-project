import { validationResult } from "express-validator";

const Validate = (req, res, next) => {
    const errors = validationResult(req);

    if (!errors.isEmpty()) {
        return res.status(400).json({
            error: errors.mapped()
        });
    }

    next();
};

export default Validate;